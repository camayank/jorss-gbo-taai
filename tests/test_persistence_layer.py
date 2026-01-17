"""
Tests for Persistence Layer - Scenario and Advisory persistence.

These tests verify that scenarios and advisory plans survive restarts
by using database-backed storage instead of in-memory dicts.
"""

import pytest
import os
import sys
import tempfile
from uuid import uuid4
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestScenarioPersistence:
    """Tests for scenario database persistence."""

    def test_scenario_persistence_import(self):
        """Test scenario persistence can be imported."""
        from database.scenario_persistence import ScenarioPersistence, get_scenario_persistence
        assert ScenarioPersistence is not None
        assert get_scenario_persistence is not None

    def test_save_and_load_scenario(self):
        """Test saving and loading a scenario."""
        from database.scenario_persistence import ScenarioPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = ScenarioPersistence(db_path)

            scenario_id = str(uuid4())
            return_id = str(uuid4())

            # Save scenario
            scenario_data = {
                "scenario_id": scenario_id,
                "return_id": return_id,
                "name": "Test Scenario",
                "description": "Test description",
                "scenario_type": "what_if",
                "status": "draft",
                "base_snapshot": {"taxpayer": {"filing_status": "single"}},
                "modifications": [
                    {"field_path": "income.wages", "original_value": 50000, "new_value": 60000}
                ],
                "result": None,
                "is_recommended": False,
            }

            saved_id = persistence.save_scenario(scenario_data)
            assert saved_id == scenario_id

            # Load scenario
            loaded = persistence.load_scenario(scenario_id)
            assert loaded is not None
            assert loaded["scenario_id"] == scenario_id
            assert loaded["name"] == "Test Scenario"
            assert loaded["scenario_type"] == "what_if"
            assert loaded["base_snapshot"]["taxpayer"]["filing_status"] == "single"
            assert len(loaded["modifications"]) == 1

    def test_update_scenario_with_result(self):
        """Test updating a scenario with calculation results."""
        from database.scenario_persistence import ScenarioPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = ScenarioPersistence(db_path)

            scenario_id = str(uuid4())
            return_id = str(uuid4())

            # Initial save
            scenario_data = {
                "scenario_id": scenario_id,
                "return_id": return_id,
                "name": "Test Scenario",
                "scenario_type": "what_if",
                "status": "draft",
                "base_snapshot": {},
                "modifications": [],
                "result": None,
            }
            persistence.save_scenario(scenario_data)

            # Update with result
            scenario_data["status"] = "calculated"
            scenario_data["result"] = {
                "total_tax": 15000,
                "savings": 2500,
                "effective_rate": 0.18,
            }
            persistence.save_scenario(scenario_data)

            # Verify update
            loaded = persistence.load_scenario(scenario_id)
            assert loaded["status"] == "calculated"
            assert loaded["result"]["total_tax"] == 15000
            assert loaded["result"]["savings"] == 2500

    def test_load_scenarios_for_return(self):
        """Test loading all scenarios for a specific return."""
        from database.scenario_persistence import ScenarioPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = ScenarioPersistence(db_path)

            return_id = str(uuid4())
            other_return_id = str(uuid4())

            # Create scenarios for return
            for i in range(3):
                persistence.save_scenario({
                    "scenario_id": str(uuid4()),
                    "return_id": return_id,
                    "name": f"Scenario {i}",
                    "scenario_type": "what_if",
                    "status": "draft",
                    "base_snapshot": {},
                    "modifications": [],
                })

            # Create scenario for other return
            persistence.save_scenario({
                "scenario_id": str(uuid4()),
                "return_id": other_return_id,
                "name": "Other Scenario",
                "scenario_type": "what_if",
                "status": "draft",
                "base_snapshot": {},
                "modifications": [],
            })

            # Load scenarios for return
            scenarios = persistence.load_scenarios_for_return(return_id)
            assert len(scenarios) == 3

            # Load scenarios for other return
            other_scenarios = persistence.load_scenarios_for_return(other_return_id)
            assert len(other_scenarios) == 1

    def test_delete_scenario(self):
        """Test deleting a scenario."""
        from database.scenario_persistence import ScenarioPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = ScenarioPersistence(db_path)

            scenario_id = str(uuid4())

            # Create and delete
            persistence.save_scenario({
                "scenario_id": scenario_id,
                "return_id": str(uuid4()),
                "name": "To Delete",
                "scenario_type": "what_if",
                "status": "draft",
                "base_snapshot": {},
                "modifications": [],
            })

            assert persistence.delete_scenario(scenario_id) is True
            assert persistence.load_scenario(scenario_id) is None
            assert persistence.delete_scenario(scenario_id) is False


class TestAdvisoryPersistence:
    """Tests for advisory plan database persistence."""

    def test_advisory_persistence_import(self):
        """Test advisory persistence can be imported."""
        from database.advisory_persistence import AdvisoryPersistence, get_advisory_persistence
        assert AdvisoryPersistence is not None
        assert get_advisory_persistence is not None

    def test_save_and_load_plan(self):
        """Test saving and loading an advisory plan."""
        from database.advisory_persistence import AdvisoryPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = AdvisoryPersistence(db_path)

            plan_id = str(uuid4())
            client_id = str(uuid4())
            return_id = str(uuid4())

            # Save plan
            plan_data = {
                "plan_id": plan_id,
                "client_id": client_id,
                "return_id": return_id,
                "tax_year": 2025,
                "total_potential_savings": 5000,
                "total_realized_savings": 0,
                "is_finalized": False,
                "recommendations": [
                    {
                        "recommendation_id": str(uuid4()),
                        "category": "retirement",
                        "priority": "immediate",
                        "title": "Max out 401k",
                        "summary": "Contribute maximum to 401k",
                        "estimated_savings": 3000,
                        "confidence_level": 0.9,
                        "complexity": "low",
                        "action_steps": [
                            {"step_number": 1, "action": "Contact HR"}
                        ],
                        "status": "proposed",
                        "irs_references": ["IRC 402(g)"],
                    }
                ],
            }

            saved_id = persistence.save_plan(plan_data)
            assert saved_id == plan_id

            # Load plan
            loaded = persistence.load_plan(plan_id)
            assert loaded is not None
            assert loaded["plan_id"] == plan_id
            assert loaded["tax_year"] == 2025
            assert loaded["total_potential_savings"] == 5000
            assert len(loaded["recommendations"]) == 1
            assert loaded["recommendations"][0]["title"] == "Max out 401k"

    def test_load_plans_for_client(self):
        """Test loading all plans for a client."""
        from database.advisory_persistence import AdvisoryPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = AdvisoryPersistence(db_path)

            client_id = str(uuid4())
            other_client_id = str(uuid4())

            # Create plans for client
            for year in [2023, 2024, 2025]:
                persistence.save_plan({
                    "plan_id": str(uuid4()),
                    "client_id": client_id,
                    "return_id": str(uuid4()),
                    "tax_year": year,
                    "total_potential_savings": 1000 * year,
                    "is_finalized": False,
                    "recommendations": [],
                })

            # Create plan for other client
            persistence.save_plan({
                "plan_id": str(uuid4()),
                "client_id": other_client_id,
                "return_id": str(uuid4()),
                "tax_year": 2025,
                "total_potential_savings": 2000,
                "is_finalized": False,
                "recommendations": [],
            })

            # Load plans for client
            plans = persistence.load_plans_for_client(client_id)
            assert len(plans) == 3

            # Load plans for other client
            other_plans = persistence.load_plans_for_client(other_client_id)
            assert len(other_plans) == 1

    def test_update_recommendation_status(self):
        """Test updating a recommendation's status."""
        from database.advisory_persistence import AdvisoryPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = AdvisoryPersistence(db_path)

            plan_id = str(uuid4())
            rec_id = str(uuid4())

            # Create plan with recommendation
            persistence.save_plan({
                "plan_id": plan_id,
                "client_id": str(uuid4()),
                "return_id": str(uuid4()),
                "tax_year": 2025,
                "is_finalized": False,
                "recommendations": [{
                    "recommendation_id": rec_id,
                    "category": "retirement",
                    "priority": "immediate",
                    "title": "Test",
                    "summary": "Test",
                    "estimated_savings": 1000,
                    "status": "proposed",
                }],
            })

            # Update status
            result = persistence.update_recommendation_status(
                rec_id, "accepted", "John CPA", None
            )
            assert result is True

            # Verify
            loaded = persistence.load_plan(plan_id)
            assert loaded["recommendations"][0]["status"] == "accepted"
            assert loaded["recommendations"][0]["status_changed_by"] == "John CPA"

    def test_record_recommendation_outcome(self):
        """Test recording actual savings for a recommendation."""
        from database.advisory_persistence import AdvisoryPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = AdvisoryPersistence(db_path)

            plan_id = str(uuid4())
            rec_id = str(uuid4())

            # Create plan
            persistence.save_plan({
                "plan_id": plan_id,
                "client_id": str(uuid4()),
                "return_id": str(uuid4()),
                "tax_year": 2025,
                "is_finalized": False,
                "recommendations": [{
                    "recommendation_id": rec_id,
                    "category": "retirement",
                    "priority": "immediate",
                    "title": "Test",
                    "summary": "Test",
                    "estimated_savings": 1000,
                    "status": "proposed",
                }],
            })

            # Record outcome
            result = persistence.record_recommendation_outcome(
                rec_id, 1200, "Exceeded estimate!"
            )
            assert result is True

            # Verify
            loaded = persistence.load_plan(plan_id)
            rec = loaded["recommendations"][0]
            assert rec["actual_savings"] == 1200
            assert rec["outcome_notes"] == "Exceeded estimate!"
            assert rec["status"] == "implemented"

    def test_delete_plan(self):
        """Test deleting a plan and its recommendations."""
        from database.advisory_persistence import AdvisoryPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            persistence = AdvisoryPersistence(db_path)

            plan_id = str(uuid4())

            # Create and delete
            persistence.save_plan({
                "plan_id": plan_id,
                "client_id": str(uuid4()),
                "return_id": str(uuid4()),
                "tax_year": 2025,
                "is_finalized": False,
                "recommendations": [{
                    "recommendation_id": str(uuid4()),
                    "category": "retirement",
                    "priority": "immediate",
                    "title": "Test",
                    "summary": "Test",
                    "estimated_savings": 1000,
                    "status": "proposed",
                }],
            })

            assert persistence.delete_plan(plan_id) is True
            assert persistence.load_plan(plan_id) is None
            assert persistence.delete_plan(plan_id) is False


class TestScenarioServicePersistence:
    """Integration tests for ScenarioService with persistence."""

    def test_scenario_service_source_uses_database(self):
        """Test that ScenarioService source code uses database instead of in-memory dict."""
        import ast
        source_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'services', 'scenario_service.py')

        with open(source_path, 'r') as f:
            source = f.read()

        # Verify persistence import is present
        assert 'from database.scenario_persistence import get_scenario_persistence' in source
        # Verify in-memory dict is NOT present
        assert 'self._scenarios: Dict[str, Scenario] = {}' not in source
        # Verify persistence is used
        assert 'self._scenario_persistence = get_scenario_persistence()' in source


class TestAdvisoryServicePersistence:
    """Integration tests for AdvisoryService with persistence."""

    def test_advisory_service_source_uses_database(self):
        """Test that AdvisoryService source code uses database instead of in-memory dict."""
        source_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'services', 'advisory_service.py')

        with open(source_path, 'r') as f:
            source = f.read()

        # Verify persistence import is present
        assert 'from database.advisory_persistence import get_advisory_persistence' in source
        # Verify in-memory dict is NOT present
        assert 'self._plans: Dict[str, AdvisoryPlan] = {}' not in source
        # Verify persistence is used
        assert 'self._advisory_persistence = get_advisory_persistence()' in source
