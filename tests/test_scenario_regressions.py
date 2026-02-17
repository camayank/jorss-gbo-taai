"""Regression tests for scenario handling edge cases."""

from __future__ import annotations

import copy
from uuid import uuid4

import pytest

from domain import Scenario, ScenarioResult, ScenarioType
from services.scenario_service import ScenarioService
from services.tax_return_service import CalculationResult, TaxReturnService


def _make_result(total_tax: float, base_tax: float) -> ScenarioResult:
    """Build a minimal scenario result for comparison tests."""
    savings = base_tax - total_tax
    savings_percent = (savings / base_tax * 100) if base_tax > 0 else 0.0
    return ScenarioResult(
        total_tax=total_tax,
        federal_tax=total_tax,
        effective_rate=0.2,
        marginal_rate=0.22,
        base_tax=base_tax,
        savings=savings,
        savings_percent=savings_percent,
        taxable_income=80000.0,
        total_deductions=10000.0,
        total_credits=0.0,
        breakdown={},
    )


def _make_scenario(name: str, return_id=None, total_tax: float = 10000.0, base_tax: float = 12000.0) -> Scenario:
    """Build a scenario with a precomputed result."""
    scenario = Scenario(
        return_id=return_id or uuid4(),
        name=name,
        scenario_type=ScenarioType.WHAT_IF,
    )
    scenario.set_result(_make_result(total_tax=total_tax, base_tax=base_tax))
    return scenario


def test_scenario_result_to_dict_round_trip_fields():
    """ScenarioResult must support dict serialization used by persistence."""
    result = _make_result(total_tax=9500.0, base_tax=12000.0)
    payload = result.to_dict()

    assert payload["total_tax"] == 9500.0
    assert payload["base_tax"] == 12000.0
    assert payload["savings"] == 2500.0
    assert isinstance(payload["computed_at"], str)


def test_strip_identity_fields_removes_sensitive_ssn_values():
    """Scenario snapshots should not retain SSN fields."""
    service = ScenarioService()
    snapshot = {
        "taxpayer": {
            "first_name": "Jane",
            "last_name": "Doe",
            "ssn": "***-**-1234",
            "spouse_ssn": "***-**-5678",
            "filing_status": "single",
        },
        "income": {"wages_salaries_tips": 100000},
    }

    sanitized = service._strip_identity_fields(snapshot)

    assert "ssn" not in sanitized["taxpayer"]
    assert "spouse_ssn" not in sanitized["taxpayer"]
    # Ensure input object is unchanged.
    assert snapshot["taxpayer"]["ssn"] == "***-**-1234"


def test_compare_scenarios_rejects_invalid_ids(monkeypatch):
    """Comparison should fail when any provided scenario id is invalid."""
    service = ScenarioService()
    valid = _make_scenario("Valid")
    valid_id = str(valid.scenario_id)
    invalid_id = str(uuid4())

    lookup = {valid_id: valid}

    monkeypatch.setattr(service, "_load_scenario_from_db", lambda sid: lookup.get(sid))
    monkeypatch.setattr(service, "_save_scenario_to_db", lambda *args, **kwargs: "ok")

    with pytest.raises(ValueError, match="Invalid or out-of-scope scenario IDs"):
        service.compare_scenarios([valid_id, invalid_id], return_id=str(valid.return_id))


def test_compare_scenarios_rejects_mixed_returns(monkeypatch):
    """Comparison should fail when scenarios belong to different returns."""
    service = ScenarioService()
    s1 = _make_scenario("A", return_id=uuid4(), total_tax=9000.0, base_tax=12000.0)
    s2 = _make_scenario("B", return_id=uuid4(), total_tax=8500.0, base_tax=12000.0)

    lookup = {str(s1.scenario_id): s1, str(s2.scenario_id): s2}

    monkeypatch.setattr(service, "_load_scenario_from_db", lambda sid: lookup.get(sid))
    monkeypatch.setattr(service, "_save_scenario_to_db", lambda *args, **kwargs: "ok")

    with pytest.raises(ValueError, match="same return"):
        service.compare_scenarios([str(s1.scenario_id), str(s2.scenario_id)])


class _DummyPersistence:
    """Minimal persistence stub for update-return error handling tests."""

    def __init__(self, payload):
        self._payload = payload
        self.saved = None

    def load_return(self, _return_id):
        return copy.deepcopy(self._payload)

    def save_return(self, session_id, tax_return_data, return_id=None):
        self.saved = (session_id, tax_return_data, return_id)
        return return_id or str(uuid4())


def test_update_return_fail_on_recalc_error_raises_and_skips_save(monkeypatch):
    """When fail_on_recalc_error=True, failed calc should abort persistence."""
    payload = {
        "tax_year": 2025,
        "taxpayer": {
            "first_name": "Jane",
            "last_name": "Doe",
            "filing_status": "single",
            "dependents": [],
        },
        "income": {"w2_forms": []},
        "deductions": {},
        "credits": {},
    }
    persistence = _DummyPersistence(payload)
    service = TaxReturnService(persistence=persistence)

    monkeypatch.setattr(
        service,
        "calculate",
        lambda *args, **kwargs: CalculationResult(success=False, errors=["bad input"]),
    )

    with pytest.raises(RuntimeError, match="Recalculation failed"):
        service.update_return(
            return_id=str(uuid4()),
            session_id="sess-1",
            updates={"income": {"w2_forms": []}},
            recalculate=True,
            fail_on_recalc_error=True,
        )

    assert persistence.saved is None
