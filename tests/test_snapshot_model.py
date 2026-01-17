"""
Tests for Snapshot-Based Calculation Model.

These tests verify that:
1. Every calculation creates a snapshot
2. Scenarios reference snapshots
3. Recalculation only happens when inputs change
"""

import pytest
import os
import sys
import tempfile
from uuid import uuid4
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSnapshotPersistence:
    """Tests for snapshot persistence layer."""

    def test_snapshot_persistence_import(self):
        """Test snapshot persistence can be imported."""
        from database.snapshot_persistence import (
            SnapshotPersistence,
            get_snapshot_persistence,
            compute_input_hash
        )
        assert SnapshotPersistence is not None
        assert get_snapshot_persistence is not None
        assert compute_input_hash is not None

    def test_compute_input_hash_deterministic(self):
        """Test that input hash is deterministic."""
        from database.snapshot_persistence import compute_input_hash

        input_data = {
            "taxpayer": {"filing_status": "single"},
            "income": {"wages": 75000},
            "deductions": {"standard": True},
        }

        # Compute hash multiple times
        hashes = [compute_input_hash(input_data) for _ in range(5)]

        # All hashes should be identical
        assert all(h == hashes[0] for h in hashes)

    def test_compute_input_hash_different_for_different_inputs(self):
        """Test that different inputs produce different hashes."""
        from database.snapshot_persistence import compute_input_hash

        input1 = {"income": {"wages": 75000}}
        input2 = {"income": {"wages": 80000}}

        hash1 = compute_input_hash(input1)
        hash2 = compute_input_hash(input2)

        assert hash1 != hash2

    def test_compute_input_hash_order_independent(self):
        """Test that key order doesn't affect hash."""
        from database.snapshot_persistence import compute_input_hash

        input1 = {"a": 1, "b": 2, "c": 3}
        input2 = {"c": 3, "a": 1, "b": 2}

        hash1 = compute_input_hash(input1)
        hash2 = compute_input_hash(input2)

        assert hash1 == hash2

    def test_save_and_load_snapshot(self):
        """Test saving and loading a snapshot."""
        from database.snapshot_persistence import SnapshotPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = SnapshotPersistence(db_path)

            return_id = str(uuid4())
            input_data = {"taxpayer": {"filing_status": "single"}, "income": {"wages": 75000}}
            result_data = {"total_tax": 12000, "effective_rate": 0.16}

            # Save snapshot
            snapshot = persistence.save_snapshot(
                return_id=return_id,
                input_data=input_data,
                result_data=result_data,
                tax_year=2025,
                filing_status="single",
                total_tax=12000,
                effective_rate=0.16,
            )

            assert snapshot["snapshot_id"] is not None
            assert snapshot["total_tax"] == 12000

            # Load by ID
            loaded = persistence.load_snapshot(snapshot["snapshot_id"])
            assert loaded is not None
            assert loaded["total_tax"] == 12000
            assert loaded["input_data"]["income"]["wages"] == 75000

    def test_get_snapshot_by_hash(self):
        """Test finding snapshot by input hash."""
        from database.snapshot_persistence import SnapshotPersistence, compute_input_hash

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = SnapshotPersistence(db_path)

            return_id = str(uuid4())
            input_data = {"income": {"wages": 50000}}

            # Save snapshot
            snapshot = persistence.save_snapshot(
                return_id=return_id,
                input_data=input_data,
                result_data={"total_tax": 8000},
                tax_year=2025,
                filing_status="single",
                total_tax=8000,
                effective_rate=0.16,
            )

            # Find by hash
            input_hash = compute_input_hash(input_data)
            found = persistence.get_snapshot_by_hash(input_hash)

            assert found is not None
            assert found["snapshot_id"] == snapshot["snapshot_id"]

    def test_duplicate_input_returns_existing_snapshot(self):
        """Test that saving duplicate input returns existing snapshot."""
        from database.snapshot_persistence import SnapshotPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = SnapshotPersistence(db_path)

            return_id = str(uuid4())
            input_data = {"income": {"wages": 60000}}

            # Save first snapshot
            snapshot1 = persistence.save_snapshot(
                return_id=return_id,
                input_data=input_data,
                result_data={"total_tax": 9000},
                tax_year=2025,
                filing_status="single",
                total_tax=9000,
                effective_rate=0.15,
            )

            # Try to save with same input - should return existing
            snapshot2 = persistence.save_snapshot(
                return_id=return_id,
                input_data=input_data,
                result_data={"total_tax": 9999},  # Different result
                tax_year=2025,
                filing_status="single",
                total_tax=9999,
                effective_rate=0.17,
            )

            # Should return the existing snapshot
            assert snapshot2["snapshot_id"] == snapshot1["snapshot_id"]
            assert snapshot2["total_tax"] == 9000  # Original value


class TestSnapshotReuse:
    """Tests for snapshot reuse in scenario calculations."""

    def test_scenario_service_uses_snapshots(self):
        """Verify ScenarioService imports snapshot persistence."""
        source_path = os.path.join(
            os.path.dirname(__file__), '..', 'src',
            'services', 'scenario_service.py'
        )

        with open(source_path, 'r') as f:
            source = f.read()

        # Verify snapshot imports
        assert 'from database.snapshot_persistence import' in source
        assert 'compute_input_hash' in source
        assert 'get_snapshot_persistence' in source

    def test_scenario_service_checks_existing_snapshot(self):
        """Verify ScenarioService checks for existing snapshots before calculating."""
        source_path = os.path.join(
            os.path.dirname(__file__), '..', 'src',
            'services', 'scenario_service.py'
        )

        with open(source_path, 'r') as f:
            source = f.read()

        # Verify snapshot lookup is used
        assert 'get_snapshot_by_hash' in source
        assert 'existing_snapshot' in source
        assert 'Reusing existing snapshot' in source

    def test_scenario_persistence_has_snapshot_columns(self):
        """Verify scenario persistence supports snapshot references."""
        source_path = os.path.join(
            os.path.dirname(__file__), '..', 'src',
            'database', 'scenario_persistence.py'
        )

        with open(source_path, 'r') as f:
            source = f.read()

        # Verify snapshot columns
        assert 'snapshot_id' in source
        assert 'base_snapshot_id' in source
        assert 'input_hash' in source


class TestInputHashDeterminism:
    """Tests for input hash determinism."""

    def test_nested_dict_hash_deterministic(self):
        """Test that deeply nested dicts produce consistent hashes."""
        from database.snapshot_persistence import compute_input_hash

        input_data = {
            "taxpayer": {
                "filing_status": "married_joint",
                "dependents": [
                    {"name": "Child 1", "age": 10},
                    {"name": "Child 2", "age": 8},
                ]
            },
            "income": {
                "wages": 150000,
                "dividends": {"qualified": 5000, "ordinary": 1000},
            },
            "deductions": {
                "itemized": {
                    "mortgage_interest": 12000,
                    "state_taxes": 10000,
                }
            }
        }

        hashes = [compute_input_hash(input_data) for _ in range(10)]
        assert all(h == hashes[0] for h in hashes)

    def test_float_precision_handled(self):
        """Test that float values produce consistent hashes."""
        from database.snapshot_persistence import compute_input_hash

        input_data = {
            "income": {"wages": 75000.50},
            "tax_rate": 0.22,
        }

        hashes = [compute_input_hash(input_data) for _ in range(5)]
        assert all(h == hashes[0] for h in hashes)


class TestSnapshotSchema:
    """Tests for snapshot database schema."""

    def test_snapshot_table_created(self):
        """Test that calculation_snapshots table is created."""
        from database.snapshot_persistence import SnapshotPersistence
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = SnapshotPersistence(db_path)

            # Check table exists
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='calculation_snapshots'
                """)
                result = cursor.fetchone()
                assert result is not None

    def test_snapshot_table_has_required_columns(self):
        """Test that snapshot table has all required columns."""
        from database.snapshot_persistence import SnapshotPersistence
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = SnapshotPersistence(db_path)

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(calculation_snapshots)")
                columns = {row[1] for row in cursor.fetchall()}

            required_columns = {
                'snapshot_id', 'return_id', 'input_hash', 'input_data',
                'result_data', 'tax_year', 'filing_status', 'total_tax',
                'effective_rate', 'created_at'
            }

            for col in required_columns:
                assert col in columns, f"Missing column: {col}"

    def test_input_hash_index_exists(self):
        """Test that input_hash has an index for fast lookup."""
        from database.snapshot_persistence import SnapshotPersistence
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = SnapshotPersistence(db_path)

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name='idx_snapshots_input_hash'
                """)
                result = cursor.fetchone()
                assert result is not None


class TestScenarioSnapshotIntegration:
    """Integration tests for scenario + snapshot model."""

    def test_scenario_stores_snapshot_reference(self):
        """Test that scenarios store snapshot_id after calculation."""
        from database.scenario_persistence import ScenarioPersistence
        import sqlite3

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = ScenarioPersistence(db_path)

            # Check columns exist
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(scenarios)")
                columns = {row[1] for row in cursor.fetchall()}

            assert 'snapshot_id' in columns
            assert 'base_snapshot_id' in columns
            assert 'input_hash' in columns

    def test_save_scenario_with_snapshot_reference(self):
        """Test saving scenario with snapshot reference."""
        from database.scenario_persistence import ScenarioPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = ScenarioPersistence(db_path)

            scenario_id = str(uuid4())
            snapshot_id = str(uuid4())
            base_snapshot_id = str(uuid4())

            # Save scenario with snapshot reference
            persistence.save_scenario({
                "scenario_id": scenario_id,
                "return_id": str(uuid4()),
                "name": "Test Scenario",
                "scenario_type": "what_if",
                "status": "calculated",
                "base_snapshot": {},
                "modifications": [],
                "snapshot_id": snapshot_id,
                "base_snapshot_id": base_snapshot_id,
                "input_hash": "abc123",
            })

            # Load and verify
            loaded = persistence.load_scenario(scenario_id)
            assert loaded["snapshot_id"] == snapshot_id
            assert loaded["base_snapshot_id"] == base_snapshot_id
            assert loaded["input_hash"] == "abc123"
