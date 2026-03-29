# tests/web/test_tools_api.py
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from web.app import app

client = TestClient(app)

VALID_STATUSES = {"single", "married_filing_jointly", "married_filing_separately",
                  "head_of_household", "qualifying_surviving_spouse"}


# --- tax-rate-lookup ---

def test_rate_lookup_valid():
    r = client.get("/api/tools/tax-rate-lookup?income=85000&filing_status=single")
    assert r.status_code == 200
    data = r.json()
    assert "marginal_rate" in data
    assert "effective_rate" in data


def test_rate_lookup_invalid_filing_status_returns_422():
    r = client.get("/api/tools/tax-rate-lookup?income=85000&filing_status=banana")
    assert r.status_code == 422


def test_rate_lookup_negative_income_clamped_to_zero():
    r = client.get("/api/tools/tax-rate-lookup?income=-5000&filing_status=single")
    assert r.status_code == 200
    assert r.json()["income"] == 0.0


# --- w4-calculator ---

def test_w4_valid():
    r = client.get("/api/tools/w4-calculator?annual_income=80000&filing_status=single")
    assert r.status_code == 200
    assert "recommendation" in r.json()


def test_w4_invalid_filing_status_returns_422():
    r = client.get("/api/tools/w4-calculator?annual_income=80000&filing_status=foobar")
    assert r.status_code == 422


def test_w4_negative_income_clamped():
    r = client.get("/api/tools/w4-calculator?annual_income=-1000&filing_status=single")
    assert r.status_code == 200
    assert r.json()["annual_tax_estimate"] >= 0


def test_w4_negative_dependents_clamped():
    r = client.get("/api/tools/w4-calculator?annual_income=50000&filing_status=single&dependents=-3")
    assert r.status_code == 200
    # negative dependents must not produce negative CTC
    assert r.json()["annual_tax_estimate"] >= 0
