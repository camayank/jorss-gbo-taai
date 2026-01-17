"""
Tests for Immutable Snapshot System.

Prompt 3: Scenario + Snapshot - Verify immutability guarantees.

Tests verify:
1. Snapshots cannot be modified after creation
2. Hash chain provides integrity verification
3. Duplicate inputs return existing snapshot (idempotency)
4. Tamper detection works correctly
5. Tenant isolation is enforced
"""

import pytest
import tempfile
import uuid
from pathlib import Path
from datetime import datetime
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestImmutableSnapshot:
    """Tests for the ImmutableSnapshot dataclass."""

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
        from audit.immutable_snapshot import ImmutableSnapshotStore
        return ImmutableSnapshotStore(db_path=temp_db)

    def test_import(self):
        """Test module can be imported."""
        from audit.immutable_snapshot import (
            ImmutableSnapshot,
            ImmutableSnapshotStore,
            compute_input_hash,
            compute_integrity_hash,
            get_immutable_snapshot_store
        )
        assert ImmutableSnapshot is not None
        assert ImmutableSnapshotStore is not None

    def test_create_snapshot(self, store):
        """Test creating an immutable snapshot."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000, "filing_status": "single"},
            result_data={"total_tax": 11000, "effective_rate": 0.1467},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467,
            taxable_income=60000.0,
            total_credits=500.0
        )

        assert snapshot.snapshot_id is not None
        assert snapshot.return_id == "return-123"
        assert snapshot.total_tax == 11000.0
        assert snapshot.integrity_hash != ""
        assert snapshot.signature != ""

    def test_snapshot_is_frozen(self, store):
        """Test that snapshot cannot be modified."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000},
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467
        )

        # Attempt to modify should raise error (frozen dataclass)
        with pytest.raises(AttributeError):
            snapshot.total_tax = 99999

        with pytest.raises(AttributeError):
            snapshot.input_json = '{"wages": 0}'

    def test_integrity_verification(self, store):
        """Test integrity verification works."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000},
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467
        )

        assert snapshot.verify_integrity() is True
        assert snapshot.verify_signature() is True

        valid, errors = snapshot.is_valid()
        assert valid is True
        assert len(errors) == 0

    def test_idempotency_same_input_returns_existing(self, store):
        """Test that same input returns existing snapshot."""
        input_data = {"wages": 75000, "filing_status": "single"}

        # Create first snapshot
        snapshot1 = store.create_snapshot(
            return_id="return-123",
            input_data=input_data,
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467
        )

        # Create second snapshot with same input
        snapshot2 = store.create_snapshot(
            return_id="return-123",
            input_data=input_data,
            result_data={"total_tax": 99999},  # Different result should be ignored
            tax_year=2025,
            filing_status="single",
            total_tax=99999.0,
            effective_rate=0.99
        )

        # Should return the same snapshot
        assert snapshot1.snapshot_id == snapshot2.snapshot_id
        assert snapshot1.total_tax == snapshot2.total_tax
        assert snapshot2.total_tax == 11000.0  # Original value, not 99999

    def test_different_input_creates_new_snapshot(self, store):
        """Test that different input creates new snapshot."""
        # Create first snapshot
        snapshot1 = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000},
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467
        )

        # Create second snapshot with different input
        snapshot2 = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 100000},  # Different wages
            result_data={"total_tax": 18000},
            tax_year=2025,
            filing_status="single",
            total_tax=18000.0,
            effective_rate=0.18
        )

        # Should be different snapshots
        assert snapshot1.snapshot_id != snapshot2.snapshot_id
        assert snapshot1.input_hash != snapshot2.input_hash


class TestChainIntegrity:
    """Tests for snapshot chain integrity."""

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
        from audit.immutable_snapshot import ImmutableSnapshotStore
        return ImmutableSnapshotStore(db_path=temp_db)

    def test_chain_links_snapshots(self, store):
        """Test that snapshots form a hash chain."""
        return_id = "return-chain-test"

        # Create first snapshot
        snapshot1 = store.create_snapshot(
            return_id=return_id,
            input_data={"wages": 50000},
            result_data={"total_tax": 5000},
            tax_year=2025,
            filing_status="single",
            total_tax=5000.0,
            effective_rate=0.10
        )

        # First snapshot has no previous
        assert snapshot1.previous_hash == ""

        # Create second snapshot
        snapshot2 = store.create_snapshot(
            return_id=return_id,
            input_data={"wages": 75000},  # Different input
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467
        )

        # Second snapshot links to first
        assert snapshot2.previous_hash == snapshot1.integrity_hash

        # Create third snapshot
        snapshot3 = store.create_snapshot(
            return_id=return_id,
            input_data={"wages": 100000},
            result_data={"total_tax": 18000},
            tax_year=2025,
            filing_status="single",
            total_tax=18000.0,
            effective_rate=0.18
        )

        # Third links to second
        assert snapshot3.previous_hash == snapshot2.integrity_hash

    def test_verify_chain_valid(self, store):
        """Test chain verification passes for valid chain."""
        return_id = "return-verify-test"

        # Create chain of snapshots
        for wages in [50000, 75000, 100000]:
            store.create_snapshot(
                return_id=return_id,
                input_data={"wages": wages},
                result_data={"total_tax": wages * 0.15},
                tax_year=2025,
                filing_status="single",
                total_tax=wages * 0.15,
                effective_rate=0.15
            )

        # Verify chain
        valid, errors = store.verify_chain(return_id)
        assert valid is True
        assert len(errors) == 0

    def test_load_chain_chronological(self, store):
        """Test loading chain returns snapshots in order."""
        return_id = "return-order-test"

        # Create snapshots
        wages_values = [50000, 75000, 100000]
        for wages in wages_values:
            store.create_snapshot(
                return_id=return_id,
                input_data={"wages": wages},
                result_data={"total_tax": wages * 0.15},
                tax_year=2025,
                filing_status="single",
                total_tax=wages * 0.15,
                effective_rate=0.15
            )

        # Load chain
        chain = store.load_chain_for_return(return_id)

        assert len(chain) == 3
        # Verify chronological order
        for i in range(len(chain) - 1):
            assert chain[i].created_at <= chain[i + 1].created_at


class TestTenantIsolation:
    """Tests for tenant isolation in snapshots."""

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
        from audit.immutable_snapshot import ImmutableSnapshotStore
        return ImmutableSnapshotStore(db_path=temp_db)

    def test_tenant_isolation_create(self, store):
        """Test snapshots are isolated by tenant."""
        input_data = {"wages": 75000}

        # Create for tenant A
        snapshot_a = store.create_snapshot(
            return_id="return-123",
            input_data=input_data,
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467,
            tenant_id="tenant-a"
        )

        # Create for tenant B (same input)
        snapshot_b = store.create_snapshot(
            return_id="return-123",
            input_data=input_data,
            result_data={"total_tax": 12000},  # Different result
            tax_year=2025,
            filing_status="single",
            total_tax=12000.0,
            effective_rate=0.16,
            tenant_id="tenant-b"
        )

        # Should be different snapshots (not reused across tenants)
        assert snapshot_a.snapshot_id != snapshot_b.snapshot_id
        assert snapshot_a.tenant_id == "tenant-a"
        assert snapshot_b.tenant_id == "tenant-b"

    def test_tenant_isolation_load(self, store):
        """Test loading respects tenant boundaries."""
        # Create for tenant A
        snapshot_a = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000},
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467,
            tenant_id="tenant-a"
        )

        # Try to load from tenant B
        loaded = store.load_snapshot(snapshot_a.snapshot_id, tenant_id="tenant-b")
        assert loaded is None  # Should not be visible

        # Load from tenant A should work
        loaded = store.load_snapshot(snapshot_a.snapshot_id, tenant_id="tenant-a")
        assert loaded is not None
        assert loaded.snapshot_id == snapshot_a.snapshot_id

    def test_tenant_chain_isolation(self, store):
        """Test chain verification is tenant-isolated."""
        return_id = "return-chain"

        # Create chain for tenant A
        for wages in [50000, 75000]:
            store.create_snapshot(
                return_id=return_id,
                input_data={"wages": wages},
                result_data={"total_tax": wages * 0.15},
                tax_year=2025,
                filing_status="single",
                total_tax=wages * 0.15,
                effective_rate=0.15,
                tenant_id="tenant-a"
            )

        # Create chain for tenant B
        for wages in [100000, 125000]:
            store.create_snapshot(
                return_id=return_id,
                input_data={"wages": wages},
                result_data={"total_tax": wages * 0.15},
                tax_year=2025,
                filing_status="single",
                total_tax=wages * 0.15,
                effective_rate=0.15,
                tenant_id="tenant-b"
            )

        # Verify tenant A chain
        chain_a = store.load_chain_for_return(return_id, tenant_id="tenant-a")
        assert len(chain_a) == 2

        # Verify tenant B chain
        chain_b = store.load_chain_for_return(return_id, tenant_id="tenant-b")
        assert len(chain_b) == 2


class TestInputNormalization:
    """Tests for input normalization and deterministic hashing."""

    def test_input_hash_deterministic(self):
        """Test that input hash is deterministic."""
        from audit.immutable_snapshot import compute_input_hash, normalize_input

        input_data = {"wages": 75000, "interest": 500, "dividends": 200}

        # Hash same data multiple times
        hashes = []
        for _ in range(100):
            json_str = normalize_input(input_data)
            hash_val = compute_input_hash(json_str)
            hashes.append(hash_val)

        # All hashes should be identical
        assert all(h == hashes[0] for h in hashes)

    def test_input_hash_key_order_independent(self):
        """Test that key order doesn't affect hash."""
        from audit.immutable_snapshot import compute_input_hash, normalize_input

        data1 = {"a": 1, "b": 2, "c": 3}
        data2 = {"c": 3, "a": 1, "b": 2}
        data3 = {"b": 2, "c": 3, "a": 1}

        hash1 = compute_input_hash(normalize_input(data1))
        hash2 = compute_input_hash(normalize_input(data2))
        hash3 = compute_input_hash(normalize_input(data3))

        assert hash1 == hash2 == hash3

    def test_input_hash_detects_changes(self):
        """Test that any change produces different hash."""
        from audit.immutable_snapshot import compute_input_hash, normalize_input

        base = {"wages": 75000, "interest": 500}
        modified = {"wages": 75001, "interest": 500}  # 1 dollar difference

        hash_base = compute_input_hash(normalize_input(base))
        hash_modified = compute_input_hash(normalize_input(modified))

        assert hash_base != hash_modified


class TestSnapshotTypes:
    """Tests for different snapshot types."""

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
        from audit.immutable_snapshot import ImmutableSnapshotStore
        return ImmutableSnapshotStore(db_path=temp_db)

    def test_calculation_snapshot(self, store):
        """Test creating a calculation snapshot."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000},
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467,
            snapshot_type="calculation"
        )

        assert snapshot.snapshot_type == "calculation"

    def test_scenario_snapshot(self, store):
        """Test creating a scenario snapshot."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000, "additional_401k": 5000},
            result_data={"total_tax": 10000},
            tax_year=2025,
            filing_status="single",
            total_tax=10000.0,
            effective_rate=0.1333,
            snapshot_type="scenario"
        )

        assert snapshot.snapshot_type == "scenario"

    def test_what_if_snapshot(self, store):
        """Test creating a what-if snapshot."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 100000},
            result_data={"total_tax": 18000},
            tax_year=2025,
            filing_status="single",
            total_tax=18000.0,
            effective_rate=0.18,
            snapshot_type="what_if"
        )

        assert snapshot.snapshot_type == "what_if"


class TestDataAccess:
    """Tests for data accessors on ImmutableSnapshot."""

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
        from audit.immutable_snapshot import ImmutableSnapshotStore
        return ImmutableSnapshotStore(db_path=temp_db)

    def test_input_data_property(self, store):
        """Test input_data property returns dict."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000, "interest": 500},
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467
        )

        input_data = snapshot.input_data
        assert isinstance(input_data, dict)
        assert input_data["wages"] == 75000
        assert input_data["interest"] == 500

    def test_result_data_property(self, store):
        """Test result_data property returns dict."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000},
            result_data={"total_tax": 11000, "brackets": [{"rate": 0.10}]},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467
        )

        result_data = snapshot.result_data
        assert isinstance(result_data, dict)
        assert result_data["total_tax"] == 11000
        assert len(result_data["brackets"]) == 1

    def test_to_dict(self, store):
        """Test to_dict serialization."""
        snapshot = store.create_snapshot(
            return_id="return-123",
            input_data={"wages": 75000},
            result_data={"total_tax": 11000},
            tax_year=2025,
            filing_status="single",
            total_tax=11000.0,
            effective_rate=0.1467
        )

        data = snapshot.to_dict()

        assert data["snapshot_id"] == snapshot.snapshot_id
        assert data["return_id"] == "return-123"
        assert data["total_tax"] == 11000.0
        assert data["integrity_hash"] == snapshot.integrity_hash
        assert isinstance(data["input_data"], dict)
        assert isinstance(data["result_data"], dict)
